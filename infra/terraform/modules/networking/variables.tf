variable "name" { type = string }
variable "azs" {
  type = list(string)
  validation {
    condition     = length(var.azs) == 2 && var.azs[0] != var.azs[1]
    error_message = "Provide exactly two distinct AZs."
  }
}
