package autotest.tko;

import com.google.gwt.json.client.JSONObject;

public class SingleTestSet extends TestSet {
    private int testIndex;
    private JSONObject initialCondition = new JSONObject();
    
    public SingleTestSet(int testIndex) {
        this.testIndex = testIndex;
    }
    
    public SingleTestSet(int testIndex, JSONObject initialCondition) {
        this(testIndex);
        this.initialCondition = initialCondition;
    }

    @Override
    public JSONObject getInitialCondition() {
        return initialCondition;
    }

    @Override
    public String getPartialSqlCondition() {
        return "test_idx = " + Integer.toString(testIndex);
    }

    @Override
    public int getTestIndex() {
        return testIndex;
    }

    @Override
    public boolean isSingleTest() {
        return true;
    }

}
