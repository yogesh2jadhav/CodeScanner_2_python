---
id: com.example.claim.CasingService.applyDefaultDischarge
title: CasingService.applyDefaultDischarge
type: method
package: com.example.claim
class_name: CasingService
method_name: applyDefaultDischarge
signature: private void applyDefaultDischarge(ClaimDataDTO data, LocalDate svc)
return_type: void
parameters:
- name: data
  type: ClaimDataDTO
- name: svc
  type: LocalDate
source_file: src/main/java/com/example/claim/CasingService.java
source_line: 86
summary: Sets dischargeDate to the maximum service date.
relationships:
  uses:
  - com.example.claim.ClaimDataDTO
---

# CasingService.applyDefaultDischarge

Sets dischargeDate to the maximum service date.
