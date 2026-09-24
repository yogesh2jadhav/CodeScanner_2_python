---
type: Index
title: Methods and Constructors
generated:
  by: java2okf/1.0.0
---

# Methods and Constructors

## com.example.Customer

- [Customer(String, String)](./com.example.Customer.Customer-741545.md)
- [Customer.getId()](./com.example.Customer.getId-401b20.md)
- [Customer.getName()](./com.example.Customer.getName-2f0961.md)
- [Customer.toString()](./com.example.Customer.toString-881c5d.md)

## com.example.Order

- [Order(String, Customer, double)](./com.example.Order.Order-089633.md)
- [Order.belongsTo(Customer)](./com.example.Order.belongsTo-5a75d5.md)
- [Order.getAmount()](./com.example.Order.getAmount-6521ea.md)
- [Order.getCustomer()](./com.example.Order.getCustomer-d48d0c.md)
- [Order.getId()](./com.example.Order.getId-4943d9.md)
- [Order.getStatus()](./com.example.Order.getStatus-b30729.md)
- [Order.markPaid()](./com.example.Order.markPaid-2fb9da.md)

## com.example.OrderRepository

- [OrderRepository.findByCustomer(Customer)](./com.example.OrderRepository.findByCustomer-78b0e3.md)
- [OrderRepository.findById(String)](./com.example.OrderRepository.findById-0485b8.md)
- [OrderRepository.save(Order)](./com.example.OrderRepository.save-b28378.md)

## com.example.OrderService

- [OrderService(OrderRepository)](./com.example.OrderService.OrderService-018dcd.md)
- [OrderService.nextId()](./com.example.OrderService.nextId-df3043.md)
- [OrderService.pay(String)](./com.example.OrderService.pay-a62790.md)
- [OrderService.placeOrder(Customer, double)](./com.example.OrderService.placeOrder-d1a758.md)
- [OrderService.totalFor(Customer)](./com.example.OrderService.totalFor-171a2e.md)
