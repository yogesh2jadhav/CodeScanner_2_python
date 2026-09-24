---
type: JavaClass
id: java-class:com.example.OrderRepository
title: OrderRepository
resource: src/main/java/com/example/OrderRepository.java
tags:
- java
- class
- com.example
generated:
  by: java2okf/1.0.0
java:
  qualifiedName: com.example.OrderRepository
  package: com.example
  kind: class
  visibility: public
  lines: 12-33
---

# OrderRepository

## Source

`src/main/java/com/example/OrderRepository.java` (lines 12–33)

## Package

[com.example](../packages/com.example.md)

## Declaration

```java
public class OrderRepository
```

## Fields

- `orders` — `Map<String,Order>` (external) (uses [Order](./com.example.Order.md), `java.lang.String` (external)) · private final

## Methods

- [findByCustomer(Customer)](../methods/com.example.OrderRepository.findByCustomer-78b0e3.md) → `List<Order>`
- [findById(String)](../methods/com.example.OrderRepository.findById-0485b8.md) → `Optional<Order>`
- [save(Order)](../methods/com.example.OrderRepository.save-b28378.md) → `void`

## Initializer Calls

- `java.util.TreeMap()` (external) — line 14

## Initializer Instantiations

- `java.util.TreeMap` (external) — line 14

## Imports

- `java.util.ArrayList` (external)
- `java.util.List` (external)
- `java.util.Map` (external)
- `java.util.Optional` (external)
- `java.util.TreeMap` (external)

## Dependencies

- [Customer](./com.example.Customer.md) — parameter
- [Order](./com.example.Order.md) — field, parameter, return type, local variable, call
- `java.lang.String` (external) — field, parameter
- `java.util.ArrayList` (external) — call
- `java.util.List` (external) — return type, local variable, call
- `java.util.Map` (external) — field, call
- `java.util.Optional` (external) — return type, call
- `java.util.TreeMap` (external) — call

## Used By

- [OrderService](./com.example.OrderService.md)

## Called By

- [OrderService.pay(String)](../methods/com.example.OrderService.pay-a62790.md) → `OrderRepository.findById(String)`
- [OrderService.placeOrder(Customer, double)](../methods/com.example.OrderService.placeOrder-d1a758.md) → `OrderRepository.save(Order)`
- [OrderService.totalFor(Customer)](../methods/com.example.OrderService.totalFor-171a2e.md) → `OrderRepository.findByCustomer(Customer)`

## Analysis Notes

This document contains facts extracted through static analysis. Unresolved relationships are explicitly marked as `UNRESOLVED`; `(external)` marks resolved targets outside the analysed sources.
