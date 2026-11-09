export function Icon({
  name,
  size = 24,
}: {
  name: 'search' | 'copy' | 'arrow' | 'document' | 'chevron';
  size?: number;
}) {
  const paths = {
    search: (
      <>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m16 16 5 5" />
      </>
    ),
    copy: (
      <>
        <path d="M8 8h12v13H8z" />
        <path d="M16 8V3H3v13h5" />
      </>
    ),
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    document: (
      <>
        <path d="M5 2h10l4 4v16H5zM15 2v5h4M8 12h8M8 16h8" />
      </>
    ),
    chevron: <path d="m9 5 7 7-7 7" />,
  };
  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.25"
      strokeLinecap="butt"
      strokeLinejoin="miter"
    >
      {paths[name]}
    </svg>
  );
}
