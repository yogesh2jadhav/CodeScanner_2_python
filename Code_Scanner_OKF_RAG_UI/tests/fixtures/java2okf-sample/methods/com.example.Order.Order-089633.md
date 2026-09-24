---
type: JavaConstructor
id: "java-constructor:com.example.Order(java.lang.String,com.example.Customer,double)"
title: Order
resource: src/main/java/com/example/Order.java
tags:
- java
- constructor
- com.example
generated:
  by: java2okf/1.0.0
java:
  declaringClass: com.example.Order
  signature: "Order(java.lang.String,com.example.Customer,double)"
  visibility: public
  lines: 16-20
---

# Order

## Declared By

[Order](../classes/com.example.Order.md)

## Signature

```java
public Order(String id, Customer customer, double amount)
```

## Source

`Order.java:16-20`

## Parameters

| Name | Type |
| --- | --- |
| `id` | `String` (external) |
| `customer` | [Customer](../classes/com.example.Customer.md) |
| `amount` | `double` |

## Called By

- [OrderService.placeOrder(Customer, double)](./com.example.OrderService.placeOrder-d1a758.md) — at line 21

## Uses

- [Customer](../classes/com.example.Customer.md) — parameter `customer`
- `java.lang.String` (external) — parameter `id`

## References

- [Order.amount](../classes/com.example.Order.md) — line 19
- [Order.customer](../classes/com.example.Order.md) — line 18
- [Order.id](../classes/com.example.Order.md) — line 17

## Resolution Status

All statically resolvable relationships are recorded. 5 outgoing relationships: 5 resolved or not applicable, 0 marked `UNRESOLVED`, 0 marked `AMBIGUOUS`.
