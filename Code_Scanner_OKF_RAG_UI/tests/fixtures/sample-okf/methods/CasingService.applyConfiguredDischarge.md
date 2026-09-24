---
id: com.example.claim.CasingService.applyConfiguredDischarge
title: CasingService.applyConfiguredDischarge
type: method
package: com.example.claim
class_name: CasingService
method_name: applyConfiguredDischarge
signature: private void applyConfiguredDischarge(ClaimDataDTO data, LocalDate svc)
return_type: void
parameters:
- name: data
  type: ClaimDataDTO
- name: svc
  type: LocalDate
source_file: src/main/java/com/example/claim/CasingService.java
source_line: 80
summary: Sets dischargeDate using the configured offset from the service date.
relationships:
  uses:
  - com.example.claim.ClaimDataDTO
---

# CasingService.applyConfiguredDischarge

Sets dischargeDate using the configured offset from the service date.
