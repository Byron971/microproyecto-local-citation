#!/usr/bin/env bash
# Reanuda partes S3 existentes de 8 MiB. No aborta partes al interrumpirse.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
manifest="config/ms_release.json"
profile="${AWS_PROFILE:-josezambrana}"
region="${AWS_REGION:-us-east-1}"
bucket="$(jq -r '.bucket' "$manifest")"
prefix="$(jq -r '.prefix' "$manifest")"
work=""
cleanup() { if [[ -n "$work" && -d "$work" ]]; then rm -rf -- "$work"; fi; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
s3() { aws --profile "$profile" --region "$region" --endpoint-url "https://s3.${region}.amazonaws.com" "$@"; }
sha() {
  python3 - "$1" <<'PY'
import hashlib,sys
h=hashlib.sha256()
with open(sys.argv[1],'rb') as f:
    for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
print(h.hexdigest())
PY
}

# Validar el inventario completo antes de escribir en S3.
python3 - "$manifest" <<'PY'
import hashlib,json,re,sys
from pathlib import Path,PurePosixPath
m=json.load(open(sys.argv[1])); identity={k:v for k,v in m.items() if k not in ('bucket','prefix','release_id')}
expected='ms-scibert-'+hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()[:16]
assert m['release_id']==expected and m['prefix']=='releases/'+expected+'/'
assert re.fullmatch(r'[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]',m['bucket'])
seen=set();root=Path.cwd()
for x in m['files']:
    p=PurePosixPath(x['path'])
    assert not p.is_absolute() and '..' not in p.parts and p.as_posix()==x['path']
    assert x['path'] not in seen and 'gold' not in x['path'].lower()
    seen.add(x['path'])
    assert (root/x['path']).resolve().is_relative_to(root)
    assert type(x['bytes']) is int and x['bytes']>0 and re.fullmatch(r'[a-f0-9]{64}',x['sha256'])
assert len(seen)==10
PY

while IFS= read -r file; do
  cleanup
  work="$(mktemp -d "${TMPDIR:-/tmp}/citas-modelos.XXXXXX")"
  key="${prefix}${file}"
  expected="$(jq -r --arg p "$file" '.files[]|select(.path==$p)|.sha256' "$manifest")"
  size="$(jq -r --arg p "$file" '.files[]|select(.path==$p)|.bytes' "$manifest")"
  [[ "$(sha "$file")" == "$expected" ]] || { echo "SHA local incorrecto: $file" >&2; exit 1; }
  [[ "$(wc -c < "$file" | tr -d ' ')" == "$size" ]] || exit 1

  if s3 s3api head-object --bucket "$bucket" --key "$key" > "$work/head.json" 2> "$work/head.err"; then
    jq -e --arg h "$expected" --argjson n "$size" '.ContentLength==$n and .Metadata.sha256==$h' "$work/head.json" >/dev/null
    echo "YA COMPLETO: $file"
    continue
  elif ! grep -Eq '404|Not Found' "$work/head.err"; then
    cat "$work/head.err" >&2
    exit 1
  fi

  if (( size < 8388608 )); then
    s3 s3 cp "$file" "s3://${bucket}/${key}" --sse AES256 --metadata "sha256=$expected" --only-show-errors
    echo "COMPLETO: $file"
    continue
  fi

  s3 s3api list-multipart-uploads --bucket "$bucket" --prefix "$key" > "$work/uploads.json"
  count="$(jq --arg k "$key" '[.Uploads[]?|select(.Key==$k)]|length' "$work/uploads.json")"
  (( count <= 1 )) || { echo "Hay múltiples subidas para $file; revisar antes de continuar" >&2; exit 1; }
  if (( count == 1 )); then
    jq -e --arg k "$key" '.Uploads[]|select(.Key==$k)|.ChecksumAlgorithm=="CRC32"' "$work/uploads.json" >/dev/null
    upload_id="$(jq -r --arg k "$key" '.Uploads[]|select(.Key==$k)|.UploadId' "$work/uploads.json")"
  else
    upload_id="$(s3 s3api create-multipart-upload --bucket "$bucket" --key "$key" --server-side-encryption AES256 --metadata "sha256=$expected" --checksum-algorithm CRC32 --query UploadId --output text)"
  fi
  s3 s3api list-parts --bucket "$bucket" --key "$key" --upload-id "$upload_id" > "$work/existing.json"
  split -b 8388608 "$file" "$work/chunk-"
  n=0
  for part in "$work"/chunk-*; do
    n=$((n+1))
    read -r crc md5 hex part_size < <(python3 - "$part" <<'PY'
import base64,hashlib,sys,zlib
d=open(sys.argv[1],'rb').read();h=hashlib.md5(d).digest()
print(base64.b64encode((zlib.crc32(d)&0xffffffff).to_bytes(4,'big')).decode(),base64.b64encode(h).decode(),h.hex(),len(d))
PY
)
    old="$(jq -c --argjson n "$n" '.Parts[]?|select(.PartNumber==$n)' "$work/existing.json")"
    if [[ -n "$old" ]]; then
      echo "$old" | jq -e --arg crc "$crc" --arg e "\"${hex}\"" --argjson size "$part_size" '.ChecksumCRC32==$crc and .ETag==$e and .Size==$size' >/dev/null
      etag="$(echo "$old" | jq -r '.ETag')"
      echo "REUTILIZADA: $file parte $n"
    else
      s3 s3api upload-part --bucket "$bucket" --key "$key" --upload-id "$upload_id" --part-number "$n" --body "$part" --content-md5 "$md5" --checksum-algorithm CRC32 --checksum-crc32 "$crc" > "$work/part.json"
      jq -e --arg crc "$crc" --arg e "\"${hex}\"" '.ChecksumCRC32==$crc and .ETag==$e' "$work/part.json" >/dev/null
      etag="$(jq -r '.ETag' "$work/part.json")"
      echo "SUBIDA: $file parte $n"
    fi
    jq -n --argjson n "$n" --arg e "$etag" --arg c "$crc" '{PartNumber:$n,ETag:$e,ChecksumCRC32:$c}' > "$work/record-${n}.json"
  done
  jq -s '{Parts:sort_by(.PartNumber)}' "$work"/record-*.json > "$work/complete.json"
  s3 s3api complete-multipart-upload --bucket "$bucket" --key "$key" --upload-id "$upload_id" --multipart-upload "file://$work/complete.json" > "$work/result.json"
  s3 s3api head-object --bucket "$bucket" --key "$key" > "$work/head.json"
  jq -e --arg h "$expected" --argjson n "$size" '.ContentLength==$n and .Metadata.sha256==$h' "$work/head.json" >/dev/null
  echo "COMPLETO: $file"
done < <(jq -r '.files[].path' "$manifest")

cleanup
work="$(mktemp -d "${TMPDIR:-/tmp}/citas-modelos.XXXXXX")"
python3 - "$manifest" "$work/release.json" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]));m.pop('bucket');m.pop('prefix')
open(sys.argv[2],'w').write(json.dumps(m,indent=2)+'\n')
PY
if s3 s3api head-object --bucket "$bucket" --key "${prefix}release.json" > "$work/head.json" 2> "$work/head.err"; then
  s3 s3 cp "s3://${bucket}/${prefix}release.json" "$work/remote.json" --only-show-errors
  cmp "$work/release.json" "$work/remote.json"
elif grep -Eq '404|Not Found' "$work/head.err"; then
  s3 s3 cp "$work/release.json" "s3://${bucket}/${prefix}release.json" --sse AES256 --only-show-errors
else
  cat "$work/head.err" >&2
  exit 1
fi
echo "PUBLICACIÓN COMPLETA: s3://${bucket}/${prefix}release.json"
echo "Falta verificar SHA-256 descargando los objetos con scripts/publicar_modelos_ms.py verify."
