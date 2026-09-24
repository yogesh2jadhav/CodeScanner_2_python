---
type: JavaMethod
id: java-method:com.example.OrderRepository.findById(java.lang.String)
title: findById
resource: src/main/java/com/example/OrderRepository.java
tags:
- java
- method
- com.example
generated:
  by: java2okf/1.0.0
java:
  declaringClass: com.example.OrderRepository
  signature: findById(java.lang.String)
  returnType: Optional<Order>
  visibility: public
  lines: 20-22
---

# findById

## Declared By

[OrderRepository](../classes/com.example.OrderRepository.md)

## Signature

```java
public Optional<Order> findById(String id)
```

## Source

`OrderRepository.java:20-22`

## Parameters

| Name | Type |
| --- | --- |
| `id` | `String` (external) |

## Returns

`Optional<Order>` (external)

## Calls

- `java.util.Map.get(java.lang.Object)` (external) — line 21
- `java.util.Optional.ofNullable(java.lang.Object)` (external) — line 21

## Called By

- [OrderService.pay(String)](./com.example.OrderService.pay-a62790.md) — at line 27

## Uses

- [Order](../classes/com.example.Order.md) — return type
- `java.lang.String` (external) — parameter `id`
- `java.util.Optional` (external) — return type

## References

- [OrderRepository.orders](../classes/com.example.OrderRepository.md) — line 21

## Resolution Status

All statically resolvable relationships are recorded. 6 outgoing relationships: 6 resolved or not applicable, 0 marked `UNRESOLVED`, 0 marked `AMBIGUOUS`.
