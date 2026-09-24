---
type: JavaMethod
id: java-method:com.example.OrderRepository.save(com.example.Order)
title: save
resource: src/main/java/com/example/OrderRepository.java
tags:
- java
- method
- com.example
generated:
  by: java2okf/1.0.0
java:
  declaringClass: com.example.OrderRepository
  signature: save(com.example.Order)
  returnType: void
  visibility: public
  lines: 16-18
---

# save

## Declared By

[OrderRepository](../classes/com.example.OrderRepository.md)

## Signature

```java
public void save(Order order)
```

## Source

`OrderRepository.java:16-18`

## Parameters

| Name | Type |
| --- | --- |
| `order` | [Order](../classes/com.example.Order.md) |

## Returns

`void`

## Calls

- [Order.getId()](./com.example.Order.getId-4943d9.md) — line 17
- `java.util.Map.put(java.lang.Object,java.lang.Object)` (external) — line 17

## Called By

- [OrderService.placeOrder(Customer, double)](./com.example.OrderService.placeOrder-d1a758.md) — at line 22

## Uses

- [Order](../classes/com.example.Order.md) — parameter `order`

## References

- [OrderRepository.orders](../classes/com.example.OrderRepository.md) — line 17

## Resolution Status

All statically resolvable relationships are recorded. 4 outgoing relationships: 4 resolved or not applicable, 0 marked `UNRESOLVED`, 0 marked `AMBIGUOUS`.
