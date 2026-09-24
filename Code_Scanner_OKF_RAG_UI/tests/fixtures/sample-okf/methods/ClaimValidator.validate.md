---
id: com.example.claim.ClaimValidator.validate
title: ClaimValidator.validate
type: method
package: com.example.claim
class_name: ClaimValidator
method_name: validate
signature: public boolean validate(ClaimDataDTO claim)
return_type: boolean
parameters:
- name: claim
  type: ClaimDataDTO
source_file: src/main/java/com/example/claim/ClaimValidator.java
source_line: 12
summary: Validates a claim; throws when ineligible.
relationships:
  calls:
  - com.example.claim.ClaimValidator.isEligible
  uses:
  - com.example.claim.ClaimDataDTO
flow:
- if: isEligible(claim)
  condition_call: isEligible
  then:
  - return: 'true'
  else:
  - throw: InvalidClaimException
---

# ClaimValidator.validate

Validates a claim; throws when ineligible.
