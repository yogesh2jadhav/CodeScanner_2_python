---
id: com.example.claim.ClaimService
title: ClaimService
type: class
package: com.example.claim
class_name: ClaimService
source_file: src/main/java/com/example/claim/ClaimService.java
source_line: 14
summary: Entry point that validates, loads and hands claims to casing.
extends:
- com.example.claim.BaseService
implements:
- com.example.claim.ClaimProcessor
depends_on:
- com.example.claim.CasingService
- com.example.claim.ClaimValidator
- com.example.claim.ClaimRepository
---

# ClaimService

Coordinates claim processing: validates the claim, loads its data and
delegates discharge-date assignment to [CasingService](CasingService.md).

## Methods
- [process](../methods/ClaimService.process.md)
- [processClaim](../methods/ClaimService.processClaim.md)
