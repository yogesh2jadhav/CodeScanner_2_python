---
id: com.example.claim.ClaimService.process
title: ClaimService.process
type: method
package: com.example.claim
class_name: ClaimService
method_name: process
signature: public void process(String claimId)
return_type: void
parameters:
- name: claimId
  type: String
source_file: src/main/java/com/example/claim/ClaimService.java
source_line: 22
summary: ClaimProcessor entry point; delegates to processClaim.
relationships:
  calls:
  - com.example.claim.ClaimService.processClaim
flow:
- call: processClaim
---

# ClaimService.process

ClaimProcessor entry point; delegates to processClaim.
