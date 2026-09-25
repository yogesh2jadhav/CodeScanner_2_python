package com.example;

/**
 * An order placed by a {@link Customer}.
 */
public class Order {

    /** Lifecycle of an order. */
    public enum Status { NEW, PAID, CANCELLED }

    private final String id;
    private final Customer customer;
    private final double amount;
    private Status status = Status.NEW;

    public Order(String id, Customer customer, double amount) {
        this.id = id;
        this.customer = customer;
        this.amount = amount;
    }

    public String getId() {
        return id;
    }

    public Customer getCustomer() {
        return customer;
    }

    public double getAmount() {
        return amount;
    }

    public Status getStatus() {
        return status;
    }

    public void markPaid() {
        if (status != Status.NEW) {
            throw new IllegalStateException("Order " + id + " cannot be paid in status " + status);
        }
        status = Status.PAID;
    }

    public boolean belongsTo(Customer other) {
        return customer.getId().equals(other.getId());
    }
}
