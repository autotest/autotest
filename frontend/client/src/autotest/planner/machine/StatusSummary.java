package autotest.planner.machine;

import autotest.common.AbstractStatusSummary;

class StatusSummary extends AbstractStatusSummary {
    static final String GOOD_STATUS = "GOOD";
    static final String RUNNING_STATUS = "RUNNING";

    private int complete;
    private int incomplete;
    private int passed;

    void addStatus(String status) {
        if (status.equals(GOOD_STATUS)) {
            complete++;
            passed++;
        } else if (status.equals(RUNNING_STATUS)) {
            incomplete++;
        } else {
            complete++;
        }
    }

    @Override
    protected int getComplete() {
        return complete;
    }
    @Override
    protected int getIncomplete() {
        return incomplete;
    }
    @Override
    protected int getPassed() {
        return passed;
    }
}
