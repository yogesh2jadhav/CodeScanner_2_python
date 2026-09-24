---
id: com.example.claim.ClaimService.processClaim
title: ClaimService.processClaim
type: method
package: com.example.claim
class_name: ClaimService
method_name: processClaim
signature: public void processClaim(String claimId)
return_type: void
parameters:
- name: claimId
  type: String
source_file: src/main/java/com/example/claim/ClaimService.java
source_line: 28
summary: Loads a claim, validates it and sends it to casing.
relationships:
  calls:
  - com.example.claim.JdbcClaimRepository.findById
  - com.example.claim.ClaimValidator.validate
  - com.example.claim.CasingService.processClaims
  - com.example.claim.BaseService.log
  uses:
  - com.example.claim.ClaimDataDTO
flow:
- call: com.example.claim.JdbcClaimRepository.findById
- call: com.example.claim.ClaimValidator.validate
- call: com.example.claim.CasingService.processClaims
- call: com.example.claim.BaseService.log
---

# ClaimService.processClaim

Loads a claim, validates it and sends it to casing.
