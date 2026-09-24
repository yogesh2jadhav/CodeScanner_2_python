---
type: JavaMethod
id: java-method:com.example.OrderRepository.findByCustomer(com.example.Customer)
title: findByCustomer
resource: src/main/java/com/example/OrderRepository.java
tags:
- java
- method
- com.example
generated:
  by: java2okf/1.0.0
java:
  declaringClass: com.example.OrderRepository
  signature: findByCustomer(com.example.Customer)
  returnType: List<Order>
  visibility: public
  lines: 24-32
---

# findByCustomer

## Declared By

[OrderRepository](../classes/com.example.OrderRepository.md)

## Signature

```java
public List<Order> findByCustomer(Customer customer)
```

## Source

`OrderRepository.java:24-32`

## Parameters

| Name | Type |
| --- | --- |
| `customer` | [Customer](../classes/com.example.Customer.md) |

## Returns

`List<Order>` (external)

## Calls

- [Order.belongsTo(Customer)](./com.example.Order.belongsTo-5a75d5.md) — line 27
- `java.util.ArrayList()` (external) — line 25
- `java.util.List.add(java.lang.Object)` (external) — line 28
- `java.util.Map.values()` (external) — line 26

## Called By

- [OrderService.totalFor(Customer)](./com.example.OrderService.totalFor-171a2e.md) — at line 34

## Uses

- [Customer](../classes/com.example.Customer.md) — parameter `customer`
- [Order](../classes/com.example.Order.md) — local variable `result`, return type
- `java.util.List` (external) — local variable `result`, return type

## Instantiates

- `java.util.ArrayList` (external) — line 25

## References

- [OrderRepository.orders](../classes/com.example.OrderRepository.md) — line 26

## Resolution Status

All statically resolvable relationships are recorded. 11 outgoing relationships: 11 resolved or not applicable, 0 marked `UNRESOLVED`, 0 marked `AMBIGUOUS`.
