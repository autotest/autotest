package autotest.tko;

import autotest.common.Utils;

import java.util.ArrayList;
import java.util.List;

class CompositeTestSet implements TestSet {
    private List<TestSet> testSets = new ArrayList<TestSet>();
    
    public void add(TestSet tests) {
        testSets.add(tests);
    }

    public String getCondition() {
        List<String> conditionParts = new ArrayList<String>();
        for(TestSet testSet : testSets) {
            conditionParts.add("(" + testSet.getCondition() + ")");
        }
        return Utils.joinStrings(" OR ", conditionParts);
    }

    public boolean isSingleTest() {
        return testSets.size() == 1 && testSets.get(0).isSingleTest();
    }
}
