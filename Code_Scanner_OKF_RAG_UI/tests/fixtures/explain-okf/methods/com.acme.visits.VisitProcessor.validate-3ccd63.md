---
type: JavaMethod
id: "java-method:com.acme.visits.VisitProcessor.validate(java.lang.String,java.util.List)"
title: validate
resource: src/main/java/com/acme/visits/VisitProcessor.java
tags:
- java
- method
- com.acme.visits
generated:
  by: java2okf/1.0.0
java:
  declaringClass: com.acme.visits.VisitProcessor
  signature: "validate(java.lang.String,java.util.List)"
  returnType: Visit
  visibility: private
  lines: 80-85
---

# validate

## Declared By

[VisitProcessor](../classes/com.acme.visits.VisitProcessor.md)

## Signature

```java
private Visit validate(String claimId, List<ClaimLine> group)
```

## Source

`VisitProcessor.java:80-85`

## Calls

- [Visit(String)](./com.acme.visits.Visit.Visit-9fccf5.md) — line 81
- [Visit.setStartDate(LocalDate)](./com.acme.visits.Visit.setStartDate-554bfb.md) — line 82
- [ClaimLine.getStartDate()](./com.acme.visits.ClaimLine.getStartDate-f7b997.md) — line 82
- [Visit.setEndDate(LocalDate)](./com.acme.visits.Visit.setEndDate-847619.md) — line 83
- [ClaimLine.getEndDate()](./com.acme.visits.ClaimLine.getEndDate-b0cd77.md) — line 83

## Called By

- [VisitProcessor.buildVisits(List, boolean)](./com.acme.visits.VisitProcessor.buildVisits-ca1cac.md) — at line 63

## Resolution Status

Statically resolvable relationships are recorded.
