---
type: JavaMethod
id: java-method:com.example.Order.belongsTo(com.example.Customer)
title: belongsTo
resource: src/main/java/com/example/Order.java
tags:
- java
- method
- com.example
generated:
  by: java2okf/1.0.0
java:
  declaringClass: com.example.Order
  signature: belongsTo(com.example.Customer)
  returnType: boolean
  visibility: public
  lines: 45-47
---

# belongsTo

## Declared By

[Order](../classes/com.example.Order.md)

## Signature

```java
public boolean belongsTo(Customer other)
```

## Source

`Order.java:45-47`

## Parameters

| Name | Type |
| --- | --- |
| `other` | [Customer](../classes/com.example.Customer.md) |

## Returns

`boolean`

## Calls

- [Customer.getId()](./com.example.Customer.getId-401b20.md) — line 46
- `java.lang.String.equals(java.lang.Object)` (external) — line 46

## Called By

- [OrderRepository.findByCustomer(Customer)](./com.example.OrderRepository.findByCustomer-78b0e3.md) — at line 27

## Uses

- [Customer](../classes/com.example.Customer.md) — parameter `other`

## References

- [Order.customer](../classes/com.example.Order.md) — line 46

## Resolution Status

All statically resolvable relationships are recorded. 4 outgoing relationships: 4 resolved or not applicable, 0 marked `UNRESOLVED`, 0 marked `AMBIGUOUS`.
