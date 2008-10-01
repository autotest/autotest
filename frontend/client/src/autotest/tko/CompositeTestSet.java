package autotest.tko;

import autotest.common.Utils;

import com.google.gwt.json.client.JSONObject;

import java.util.ArrayList;
import java.util.List;

class CompositeTestSet extends TestSet {
    private List<TestSet> testSets = new ArrayList<TestSet>();
    
    public void add(TestSet tests) {
        testSets.add(tests);
    }
    
    @Override
    public JSONObject getInitialCondition() {
        // we assume the initial condition is the same for all tests
        assert !testSets.isEmpty();
        return testSets.get(0).getInitialCondition();
    }

    @Override
    public String getPartialSqlCondition() {
        List<String> conditionParts = new ArrayList<String>();
        for(TestSet testSet : testSets) {
            conditionParts.add("(" + testSet.getPartialSqlCondition() + ")");
        }
        return Utils.joinStrings(" OR ", conditionParts);
    }

    @Override
    public boolean isSingleTest() {
        return testSets.size() == 1 && testSets.get(0).isSingleTest();
    }

    @Override
    public int getTestIndex() {
        if (!isSingleTest()) {
            throw new UnsupportedOperationException();
        }
        return testSets.get(0).getTestIndex();
    }
}
