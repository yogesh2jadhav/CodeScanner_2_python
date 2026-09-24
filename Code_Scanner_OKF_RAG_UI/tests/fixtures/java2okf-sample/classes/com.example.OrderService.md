---
type: JavaClass
id: java-class:com.example.OrderService
title: OrderService
resource: src/main/java/com/example/OrderService.java
tags:
- java
- class
- com.example
generated:
  by: java2okf/1.0.0
java:
  qualifiedName: com.example.OrderService
  package: com.example
  kind: class
  visibility: public
  lines: 8-42
---

# OrderService

## Source

`src/main/java/com/example/OrderService.java` (lines 8–42)

## Package

[com.example](../packages/com.example.md)

## Declaration

```java
public class OrderService
```

## Fields

- `repository` — [OrderRepository](./com.example.OrderRepository.md) · private final
- `sequence` — `int` · private

## Constructors

- [OrderService(OrderRepository)](../methods/com.example.OrderService.OrderService-018dcd.md)

## Methods

- [nextId()](../methods/com.example.OrderService.nextId-df3043.md) → `String`
- [pay(String)](../methods/com.example.OrderService.pay-a62790.md) → `Order`
- [placeOrder(Customer, double)](../methods/com.example.OrderService.placeOrder-d1a758.md) → `Order`
- [totalFor(Customer)](../methods/com.example.OrderService.totalFor-171a2e.md) → `double`

## Imports

- `java.util.List` (external)

## Dependencies

- [Customer](./com.example.Customer.md) — parameter
- [Order](./com.example.Order.md) — return type, local variable, call, type reference
- [OrderRepository](./com.example.OrderRepository.md) — field, parameter, call
- `java.lang.IllegalArgumentException` (external) — call
- `java.lang.String` (external) — parameter, return type
- `java.util.Collection` (external) — call
- `java.util.List` (external) — local variable
- `java.util.Optional` (external) — call
- `java.util.stream.DoubleStream` (external) — call
- `java.util.stream.Stream` (external) — call

## Analysis Notes

This document contains facts extracted through static analysis. Unresolved relationships are explicitly marked as `UNRESOLVED`; `(external)` marks resolved targets outside the analysed sources.
