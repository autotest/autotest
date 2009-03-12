package autotest.tko;

import autotest.common.CustomHistory.HistoryToken;

interface TestSelectionListener {
    public void onSelectTest(int testId);
    public HistoryToken getSelectTestHistoryToken(int testId);
}
