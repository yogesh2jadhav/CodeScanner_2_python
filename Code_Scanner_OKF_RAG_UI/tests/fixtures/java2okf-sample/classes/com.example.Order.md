---
type: JavaClass
id: java-class:com.example.Order
title: Order
resource: src/main/java/com/example/Order.java
tags:
- java
- class
- com.example
generated:
  by: java2okf/1.0.0
java:
  qualifiedName: com.example.Order
  package: com.example
  kind: class
  visibility: public
  lines: 6-48
---

# Order

## Source

`src/main/java/com/example/Order.java` (lines 6–48)

## Package

[com.example](../packages/com.example.md)

## Declaration

```java
public class Order
```

## Fields

- `id` — `String` (external) · private final
- `customer` — [Customer](./com.example.Customer.md) · private final
- `amount` — `double` · private final
- `status` — [Status](../enums/com.example.Order.Status.md) · private

## Constructors

- [Order(String, Customer, double)](../methods/com.example.Order.Order-089633.md)

## Methods

- [belongsTo(Customer)](../methods/com.example.Order.belongsTo-5a75d5.md) → `boolean`
- [getAmount()](../methods/com.example.Order.getAmount-6521ea.md) → `double`
- [getCustomer()](../methods/com.example.Order.getCustomer-d48d0c.md) → `Customer`
- [getId()](../methods/com.example.Order.getId-4943d9.md) → `String`
- [getStatus()](../methods/com.example.Order.getStatus-b30729.md) → `Status`
- [markPaid()](../methods/com.example.Order.markPaid-2fb9da.md) → `void`

## Nested Types

- [Status](../enums/com.example.Order.Status.md)

## Dependencies

- [Customer](./com.example.Customer.md) — field, parameter, return type, call
- [Status](../enums/com.example.Order.Status.md) — field, return type
- `java.lang.IllegalStateException` (external) — call
- `java.lang.String` (external) — field, parameter, return type, call

## Used By

- [OrderRepository](./com.example.OrderRepository.md)
- [OrderService](./com.example.OrderService.md)

## Called By

- [OrderRepository.findByCustomer(Customer)](../methods/com.example.OrderRepository.findByCustomer-78b0e3.md) → `Order.belongsTo(Customer)`
- [OrderRepository.save(Order)](../methods/com.example.OrderRepository.save-b28378.md) → `Order.getId()`
- [OrderService.pay(String)](../methods/com.example.OrderService.pay-a62790.md) → `Order.markPaid()`
- [OrderService.placeOrder(Customer, double)](../methods/com.example.OrderService.placeOrder-d1a758.md) → `Order(String, Customer, double)`

## Analysis Notes

This document contains facts extracted through static analysis. Unresolved relationships are explicitly marked as `UNRESOLVED`; `(external)` marks resolved targets outside the analysed sources.
