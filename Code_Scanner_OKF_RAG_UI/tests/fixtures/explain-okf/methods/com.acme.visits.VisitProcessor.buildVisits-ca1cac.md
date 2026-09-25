---
type: JavaMethod
id: "java-method:com.acme.visits.VisitProcessor.buildVisits(java.util.List,boolean)"
title: buildVisits
resource: src/main/java/com/acme/visits/VisitProcessor.java
tags:
- java
- method
- com.acme.visits
generated:
  by: java2okf/1.0.0
java:
  declaringClass: com.acme.visits.VisitProcessor
  signature: "buildVisits(java.util.List,boolean)"
  returnType: List<Visit>
  visibility: public
  lines: 28-73
---

# buildVisits

## Declared By

[VisitProcessor](../classes/com.acme.visits.VisitProcessor.md)

## Signature

```java
public List<Visit> buildVisits(List<ClaimLine> lines, boolean flagMissingEnd) throws VisitException
```

## Source

`VisitProcessor.java:28-73`

## Calls

- `java.util.List.isEmpty()` (external) — line 30
- [VisitException(String)](./com.acme.visits.VisitException.VisitException-1fe7c1.md) — lines 31, 68
- `java.util.Collection.stream()` (external) — lines 35, 39
- [ClaimLine.getStartDate()](./com.acme.visits.ClaimLine.getStartDate-f7b997.md) — line 36
- `java.util.stream.Collectors.groupingBy(java.util.function.Function)` (external) — line 37
- [ClaimLine.setStartDate(LocalDate)](./com.acme.visits.ClaimLine.setStartDate-89acd6.md) — line 43
- [ClaimLine.getEndDate()](./com.acme.visits.ClaimLine.getEndDate-b0cd77.md) — line 47
- [ClaimLine.getToDate()](./com.acme.visits.ClaimLine.getToDate-0aedc2.md) — line 48
- [ClaimLine.setEndDate(LocalDate)](./com.acme.visits.ClaimLine.setEndDate-a02b42.md) — line 48
- [ClaimLine.setMissingEndFlag(int)](./com.acme.visits.ClaimLine.setMissingEndFlag-a48e37.md) — lines 50, 52
- [VisitProcessor.groupByClaim(List)](./com.acme.visits.VisitProcessor.groupByClaim-cced61.md) — line 61
- [VisitProcessor.validate(String, List)](./com.acme.visits.VisitProcessor.validate-3ccd63.md) — line 63
- `java.util.List.add(java.lang.Object)` (external) — line 63
- [VisitRepository.saveAll(List)](./com.acme.visits.VisitRepository.saveAll-d1fe02.md) — line 65
- `audit.record(..)` — UNRESOLVED — line 66
- `java.util.List.size()` (external) — lines 66, 71

## Resolution Status

Statically resolvable relationships are recorded.
