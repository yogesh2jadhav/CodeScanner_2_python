---
type: JavaMethod
id: java-method:com.example.OrderService.pay(java.lang.String)
title: pay
resource: src/main/java/com/example/OrderService.java
tags:
- java
- method
- com.example
generated:
  by: java2okf/1.0.0
java:
  declaringClass: com.example.OrderService
  signature: pay(java.lang.String)
  returnType: Order
  visibility: public
  lines: 26-31
---

# pay

## Declared By

[OrderService](../classes/com.example.OrderService.md)

## Signature

```java
public Order pay(String orderId)
```

## Source

`OrderService.java:26-31`

## Parameters

| Name | Type |
| --- | --- |
| `orderId` | `String` (external) |

## Returns

[Order](../classes/com.example.Order.md)

## Calls

- [Order.markPaid()](./com.example.Order.markPaid-2fb9da.md) — line 29
- [OrderRepository.findById(String)](./com.example.OrderRepository.findById-0485b8.md) — line 27
- `java.lang.IllegalArgumentException(java.lang.String)` (external) — line 28
- `java.util.Optional.orElseThrow(java.util.function.Supplier)` (external) — line 27

## Uses

- [Order](../classes/com.example.Order.md) — local variable `order`, return type
- `java.lang.String` (external) — parameter `orderId`

## Instantiates

- `java.lang.IllegalArgumentException` (external) — line 28

## References

- [OrderService.repository](../classes/com.example.OrderService.md) — line 27

## Resolution Status

All statically resolvable relationships are recorded. 9 outgoing relationships: 9 resolved or not applicable, 0 marked `UNRESOLVED`, 0 marked `AMBIGUOUS`.
