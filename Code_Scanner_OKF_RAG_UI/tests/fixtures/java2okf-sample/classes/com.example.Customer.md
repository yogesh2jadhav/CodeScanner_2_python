---
type: JavaClass
id: java-class:com.example.Customer
title: Customer
resource: src/main/java/com/example/Customer.java
tags:
- java
- class
- com.example
generated:
  by: java2okf/1.0.0
java:
  qualifiedName: com.example.Customer
  package: com.example
  kind: class
  visibility: public
  lines: 8-30
---

# Customer

## Source

`src/main/java/com/example/Customer.java` (lines 8–30)

## Package

[com.example](../packages/com.example.md)

## Declaration

```java
public class Customer
```

## Fields

- `id` — `String` (external) · private final
- `name` — `String` (external) · private final

## Constructors

- [Customer(String, String)](../methods/com.example.Customer.Customer-741545.md)

## Methods

- [getId()](../methods/com.example.Customer.getId-401b20.md) → `String`
- [getName()](../methods/com.example.Customer.getName-2f0961.md) → `String`
- [toString()](../methods/com.example.Customer.toString-881c5d.md) → `String`

## Imports

- `java.util.Objects` (external)

## Dependencies

- `java.lang.Override` (external) — annotation
- `java.lang.String` (external) — field, parameter, return type
- `java.util.Objects` (external) — call

## Used By

- [Order](./com.example.Order.md)
- [OrderRepository](./com.example.OrderRepository.md)
- [OrderService](./com.example.OrderService.md)

## Called By

- [Order.belongsTo(Customer)](../methods/com.example.Order.belongsTo-5a75d5.md) → `Customer.getId()`

## Analysis Notes

This document contains facts extracted through static analysis. Unresolved relationships are explicitly marked as `UNRESOLVED`; `(external)` marks resolved targets outside the analysed sources.
