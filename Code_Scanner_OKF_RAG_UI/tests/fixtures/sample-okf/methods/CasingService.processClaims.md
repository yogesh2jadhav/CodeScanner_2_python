---
id: com.example.claim.CasingService.processClaims
title: CasingService.processClaims
type: method
package: com.example.claim
class_name: CasingService
method_name: processClaims
signature: public void processClaims(List<ClaimDataDTO> claims)
return_type: void
parameters:
- name: claims
  type: List<ClaimDataDTO>
source_file: src/main/java/com/example/claim/CasingService.java
source_line: 42
summary: Assigns the discharge date for each claim, using configuration when enabled.
relationships:
  calls:
  - com.example.claim.CasingService.getClaimData
  - com.example.claim.CasingService.calculateServiceDate
  - com.example.claim.CasingService.checkConfiguration
  - com.example.claim.CasingService.applyConfiguredDischarge
  - com.example.claim.CasingService.applyDefaultDischarge
  - com.example.claim.ClaimRepository.save
  uses:
  - com.example.claim.ClaimDataDTO
flow:
- loop: 'for (ClaimDataDTO claim : claims)'
  body:
  - call: getClaimData
  - call: calculateServiceDate
  - if: checkConfiguration()
    condition_call: checkConfiguration
    then:
    - call: applyConfiguredDischarge
    else:
    - call: applyDefaultDischarge
  - call: com.example.claim.ClaimRepository.save
- return: void
---

# CasingService.processClaims

For every claim: load claim data, calculate the service date, then set
`dischargeDate`. If the casing configuration is enabled the configured
discharge rule is applied, otherwise the discharge date is set to the
maximum service date. The claim is then saved.

```java
for (ClaimDataDTO claim : claims) {
    ClaimDataDTO data = getClaimData(claim.getClaimId());
    LocalDate svc = calculateServiceDate(data);
    if (checkConfiguration()) {
        applyConfiguredDischarge(data, svc);
    } else {
        applyDefaultDischarge(data, svc);
    }
    repository.save(data);
}
```
