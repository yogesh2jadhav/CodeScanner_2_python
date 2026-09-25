---
type: JavaMethod
id: "java-method:com.acme.visits.VisitProcessor.groupByClaim(java.util.List)"
title: groupByClaim
resource: src/main/java/com/acme/visits/VisitProcessor.java
tags:
- java
- method
- com.acme.visits
generated:
  by: java2okf/1.0.0
java:
  declaringClass: com.acme.visits.VisitProcessor
  signature: "groupByClaim(java.util.List)"
  returnType: Map<String,List<ClaimLine>>
  visibility: private
  lines: 75-77
---

# groupByClaim

## Declared By

[VisitProcessor](../classes/com.acme.visits.VisitProcessor.md)

## Signature

```java
private Map<String, List<ClaimLine>> groupByClaim(List<ClaimLine> lines)
```

## Source

`VisitProcessor.java:75-77`

## Calls

- `java.util.Collection.stream()` (external) — line 76
- `java.util.stream.Collectors.groupingBy(java.util.function.Function)` (external) — line 76

## Called By

- [VisitProcessor.buildVisits(List, boolean)](./com.acme.visits.VisitProcessor.buildVisits-ca1cac.md) — at line 61

## Resolution Status

Statically resolvable relationships are recorded.
