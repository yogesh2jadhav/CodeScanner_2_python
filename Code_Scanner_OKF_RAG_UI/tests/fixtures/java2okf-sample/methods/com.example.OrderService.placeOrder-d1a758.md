---
type: JavaMethod
id: "java-method:com.example.OrderService.placeOrder(com.example.Customer,double)"
title: placeOrder
resource: src/main/java/com/example/OrderService.java
tags:
- java
- method
- com.example
generated:
  by: java2okf/1.0.0
java:
  declaringClass: com.example.OrderService
  signature: "placeOrder(com.example.Customer,double)"
  returnType: Order
  visibility: public
  lines: 17-24
---

# placeOrder

## Declared By

[OrderService](../classes/com.example.OrderService.md)

## Signature

```java
public Order placeOrder(Customer customer, double amount)
```

## Source

`OrderService.java:17-24`

## Parameters

| Name | Type |
| --- | --- |
| `customer` | [Customer](../classes/com.example.Customer.md) |
| `amount` | `double` |

## Returns

[Order](../classes/com.example.Order.md)

## Calls

- [Order(String, Customer, double)](./com.example.Order.Order-089633.md) — line 21
- [OrderRepository.save(Order)](./com.example.OrderRepository.save-b28378.md) — line 22
- [OrderService.nextId()](./com.example.OrderService.nextId-df3043.md) — line 21
- `java.lang.IllegalArgumentException(java.lang.String)` (external) — line 19

## Uses

- [Customer](../classes/com.example.Customer.md) — parameter `customer`
- [Order](../classes/com.example.Order.md) — local variable `order`, return type

## Instantiates

- [Order](../classes/com.example.Order.md) — line 21
- `java.lang.IllegalArgumentException` (external) — line 19

## References

- [OrderService.repository](../classes/com.example.OrderService.md) — line 22

## Resolution Status

All statically resolvable relationships are recorded. 10 outgoing relationships: 10 resolved or not applicable, 0 marked `UNRESOLVED`, 0 marked `AMBIGUOUS`.
