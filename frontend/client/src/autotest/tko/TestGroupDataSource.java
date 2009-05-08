package autotest.tko;

import autotest.common.JSONArrayList;
import autotest.common.Utils;
import autotest.common.table.RpcDataSource;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

class TestGroupDataSource extends RpcDataSource {
    private static final String NUM_GROUPS_RPC = "get_num_groups";
    private static final String GROUP_COUNTS_RPC = "get_group_counts";
    private static final String STATUS_COUNTS_RPC = "get_status_counts";
    private static final String LATEST_TESTS_RPC = "get_latest_tests";
    public static final String GROUP_COUNT_FIELD = "group_count";
    public static final String PASS_COUNT_FIELD = "pass_count";
    public static final String COMPLETE_COUNT_FIELD = "complete_count";
    public static final String INCOMPLETE_COUNT_FIELD = "incomplete_count";
    
    private JSONArray groupByFields;
    private JSONArray headerGroups;
    private JSONArray headerGroupValues;
    private boolean skipNumResults = false;
    private JSONObject queryParameters;
    
    public static TestGroupDataSource getTestGroupDataSource() {
        return new TestGroupDataSource(GROUP_COUNTS_RPC);
    }
    
    public static TestGroupDataSource getStatusCountDataSource() {
        return new TestGroupDataSource(STATUS_COUNTS_RPC);
    }
    
    public static TestGroupDataSource getLatestTestsDataSource() {
        return new TestGroupDataSource(LATEST_TESTS_RPC);
    }
    
    // force construction to go through above factory methods
    private TestGroupDataSource(String dataMethodName) {
        super(dataMethodName, NUM_GROUPS_RPC);
    }

    @Override
    public void updateData(JSONObject params, DataCallback callback) {
        JSONObject fullParams = Utils.copyJSONObject(params);
        Utils.updateObject(fullParams, queryParameters);
        fullParams.put("group_by", groupByFields);
        if (headerGroups != null) {
            fullParams.put("header_groups", headerGroups);
        }

        if (skipNumResults) {
            filterParams = fullParams;
            numResults = 0;
            callback.onGotData(numResults);
        } else {
            super.updateData(fullParams, callback);
        }
    }

    public JSONObject getFullRequestParams(JSONObject conditionParams) {
        JSONObject fullParams = Utils.copyJSONObject(conditionParams);
        Utils.updateObject(fullParams, queryParameters);
        fullParams.put("group_by", groupByFields);
        if (headerGroups != null) {
            fullParams.put("header_groups", headerGroups);
        }
        return fullParams;
    }

    @Override
    /**
     * Process the groups, which come simply as lists, into JSONObjects.
     */
    protected JSONArray handleJsonResult(JSONValue result) {
        JSONObject resultObject = result.isObject();
        headerGroupValues = resultObject.get("header_values").isArray();
        return resultObject.get("groups").isArray();
    }
    
    public void setGroupColumns(String[] columns) {
        groupByFields = new JSONArray();
        for (String field : columns) {
            groupByFields.set(groupByFields.size(), new JSONString(field));
        }
        headerGroups = null;
    }
    
    public void setHeaderGroups(List<List<String>> headerFieldGroups) {
        groupByFields = new JSONArray();
        headerGroups = new JSONArray();
        for (List<String> headerGroup : headerFieldGroups) {
            headerGroups.set(headerGroups.size(), Utils.stringsToJSON(headerGroup));
            for(String field : headerGroup) {
                groupByFields.set(groupByFields.size(), new JSONString(field));
            }
        }
    }
    
    /**
     * Get a list of values for the header group with the given index, as specified to 
     * setHeaderGroups().
     */
    public List<List<String>> getHeaderGroupValues(int groupIndex) {
        JSONArray headerList = headerGroupValues.get(groupIndex).isArray();
        List<List<String>> headerValueList = new ArrayList<List<String>>();
        for (JSONArray header : new JSONArrayList<JSONArray>(headerList)) {
            headerValueList.add(Arrays.asList(Utils.JSONtoStrings(header)));
        }
        return headerValueList;
    }

    public void setSkipNumResults(boolean skipNumResults) {
        this.skipNumResults = skipNumResults;
    }

    public void setQueryParameters(JSONObject queryParameters) {
        this.queryParameters = queryParameters;
    }
}
