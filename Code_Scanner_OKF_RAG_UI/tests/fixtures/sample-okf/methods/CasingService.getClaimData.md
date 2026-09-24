---
id: com.example.claim.CasingService.getClaimData
title: CasingService.getClaimData
type: method
package: com.example.claim
class_name: CasingService
method_name: getClaimData
signature: private ClaimDataDTO getClaimData(String claimId)
return_type: ClaimDataDTO
parameters:
- name: claimId
  type: String
source_file: src/main/java/com/example/claim/CasingService.java
source_line: 60
summary: Loads claim data from the repository.
relationships:
  calls:
  - com.example.claim.ClaimRepository.findById
  uses:
  - com.example.claim.ClaimDataDTO
flow:
- call: com.example.claim.ClaimRepository.findById
- return: claim data
---

# CasingService.getClaimData

Loads claim data from the repository.
