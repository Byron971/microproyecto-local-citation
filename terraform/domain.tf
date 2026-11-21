locals {
  # El registro elimina espacios externos; enviar ya normalizado evita diferencias tras apply.
  domain_contact = var.contact == null ? null : {
    for key, value in var.contact : key => value == null ? null : trimspace(value)
  }
}

# Registro, DNS y aplicación comparten el backend existente.
resource "aws_route53domains_domain" "app" {
  count              = local.frontend_custom_domain ? 1 : 0
  provider           = aws.virginia
  domain_name        = var.frontend_domain_name
  duration_in_years  = 1
  auto_renew         = false
  transfer_lock      = true
  admin_privacy      = true
  registrant_privacy = true
  tech_privacy       = true
  billing_privacy    = true
  # El proveedor puede completar facturación desde AWS y mostrarla sin la marca sensitive.
  # Declararla explícitamente conserva esa marca en el plan.
  billing_contact = local.domain_contact == null ? null : sensitive([merge(local.domain_contact, {
    contact_type      = "PERSON"
    address_line_2    = null
    organization_name = null
    fax               = null
    extra_param       = null
  })])

  dynamic "admin_contact" {
    for_each = local.domain_contact[*]
    content {
      contact_type   = "PERSON"
      first_name     = admin_contact.value.first_name
      last_name      = admin_contact.value.last_name
      address_line_1 = admin_contact.value.address_line_1
      city           = admin_contact.value.city
      state          = admin_contact.value.state
      country_code   = admin_contact.value.country_code
      zip_code       = admin_contact.value.zip_code
      phone_number   = admin_contact.value.phone_number
      email          = admin_contact.value.email
    }
  }
  dynamic "registrant_contact" {
    for_each = local.domain_contact[*]
    content {
      contact_type   = "PERSON"
      first_name     = registrant_contact.value.first_name
      last_name      = registrant_contact.value.last_name
      address_line_1 = registrant_contact.value.address_line_1
      city           = registrant_contact.value.city
      state          = registrant_contact.value.state
      country_code   = registrant_contact.value.country_code
      zip_code       = registrant_contact.value.zip_code
      phone_number   = registrant_contact.value.phone_number
      email          = registrant_contact.value.email
    }
  }
  dynamic "tech_contact" {
    for_each = local.domain_contact[*]
    content {
      contact_type   = "PERSON"
      first_name     = tech_contact.value.first_name
      last_name      = tech_contact.value.last_name
      address_line_1 = tech_contact.value.address_line_1
      city           = tech_contact.value.city
      state          = tech_contact.value.state
      country_code   = tech_contact.value.country_code
      zip_code       = tech_contact.value.zip_code
      phone_number   = tech_contact.value.phone_number
      email          = tech_contact.value.email
    }
  }
  lifecycle {
    prevent_destroy = true
    precondition {
      condition     = var.contact != null
      error_message = "Completa contact en terraform/terraform.tfvars para registrar el dominio."
    }
    precondition {
      condition     = data.aws_caller_identity.current.account_id == "646941583111"
      error_message = "El registro está autorizado para la cuenta del perfil josezambrana (646941583111)."
    }
  }
}
