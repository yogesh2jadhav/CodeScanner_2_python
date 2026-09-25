package com.acme.visits;

import java.time.LocalDate;

public class Visit {
    private final String claimId;
    private LocalDate startDate;
    private LocalDate endDate;

    public Visit(String claimId) { this.claimId = claimId; }
    public void setStartDate(LocalDate d) { this.startDate = d; }
    public void setEndDate(LocalDate d) { this.endDate = d; }
}
