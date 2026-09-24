---
id: com.example.claim.CasingService
title: CasingService
type: class
package: com.example.claim
class_name: CasingService
source_file: src/main/java/com/example/claim/CasingService.java
source_line: 20
summary: Assigns discharge dates to claims based on service dates and configuration.
depends_on:
- com.example.claim.ClaimRepository
uses:
- com.example.claim.ClaimDataDTO
---

# CasingService

Groups claims into cases and assigns the discharge date. The discharge date
is derived from the latest service date, or from a configured default.

## Methods
- [processClaims](../methods/CasingService.processClaims.md)
- [getClaimData](../methods/CasingService.getClaimData.md)
- [calculateServiceDate](../methods/CasingService.calculateServiceDate.md)
- [checkConfiguration](../methods/CasingService.checkConfiguration.md)
- [applyConfiguredDischarge](../methods/CasingService.applyConfiguredDischarge.md)
- [applyDefaultDischarge](../methods/CasingService.applyDefaultDischarge.md)
