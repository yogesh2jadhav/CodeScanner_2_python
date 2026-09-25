package com.acme.visits;

import java.time.LocalDate;

public class ClaimLine {
    private String claimId;
    private LocalDate fromDate;
    private LocalDate toDate;
    private LocalDate startDate;
    private LocalDate endDate;
    private int missingEndFlag;

    public String getClaimId() { return claimId; }
    public LocalDate getFromDate() { return fromDate; }
    public LocalDate getToDate() { return toDate; }
    public LocalDate getStartDate() { return startDate; }
    public void setStartDate(LocalDate d) { this.startDate = d; }
    public LocalDate getEndDate() { return endDate; }
    public void setEndDate(LocalDate d) { this.endDate = d; }
    public void setMissingEndFlag(int f) { this.missingEndFlag = f; }
}
