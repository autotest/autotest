package autotest.tko;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

abstract class TestSet {
    /**
     * Get the full condition args for this test set.
     */
    public abstract JSONObject getInitialCondition();
    /**
     * Get the SQL condition for this test set within the global set.
     */
    public abstract String getPartialSqlCondition();
    public abstract boolean isSingleTest();
    public abstract int getTestIndex();
    
    public JSONObject getCondition() {
        JSONObject condition = getInitialCondition();
        String sqlCondition = TkoUtils.getSqlCondition(condition); 
        sqlCondition = TkoUtils.joinWithParens(" AND ", sqlCondition, getPartialSqlCondition());
        condition.put("extra_where", new JSONString(sqlCondition));
        return condition;
    }
}
