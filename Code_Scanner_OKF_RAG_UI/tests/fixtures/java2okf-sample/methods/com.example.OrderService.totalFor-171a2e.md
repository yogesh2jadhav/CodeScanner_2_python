---
type: JavaMethod
id: java-method:com.example.OrderService.totalFor(com.example.Customer)
title: totalFor
resource: src/main/java/com/example/OrderService.java
tags:
- java
- method
- com.example
generated:
  by: java2okf/1.0.0
java:
  declaringClass: com.example.OrderService
  signature: totalFor(com.example.Customer)
  returnType: double
  visibility: public
  lines: 33-36
---

# totalFor

## Declared By

[OrderService](../classes/com.example.OrderService.md)

## Signature

```java
public double totalFor(Customer customer)
```

## Source

`OrderService.java:33-36`

## Parameters

| Name | Type |
| --- | --- |
| `customer` | [Customer](../classes/com.example.Customer.md) |

## Returns

`double`

## Calls

- [OrderRepository.findByCustomer(Customer)](./com.example.OrderRepository.findByCustomer-78b0e3.md) — line 34
- `java.util.Collection.stream()` (external) — line 35
- `java.util.stream.DoubleStream.sum()` (external) — line 35
- `java.util.stream.Stream.mapToDouble(java.util.function.ToDoubleFunction)` (external) — line 35

## Uses

- [Customer](../classes/com.example.Customer.md) — parameter `customer`
- [Order](../classes/com.example.Order.md) — local variable `orders`
- `java.util.List` (external) — local variable `orders`

## References

- [Order.getAmount()](./com.example.Order.getAmount-6521ea.md) — line 35
- [OrderService.repository](../classes/com.example.OrderService.md) — line 34

## Resolution Status

All statically resolvable relationships are recorded. 9 outgoing relationships: 9 resolved or not applicable, 0 marked `UNRESOLVED`, 0 marked `AMBIGUOUS`.
