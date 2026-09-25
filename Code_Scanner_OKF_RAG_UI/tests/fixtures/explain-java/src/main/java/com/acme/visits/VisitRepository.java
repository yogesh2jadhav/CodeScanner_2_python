package com.acme.visits;

import java.util.List;

public interface VisitRepository {

    void saveAll(List<Visit> visits);

    int count(String sql, String batchId);
}
