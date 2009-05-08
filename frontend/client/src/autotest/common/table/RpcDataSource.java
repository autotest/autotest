package autotest.common.table;

import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.Utils;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

/**
 * Data source that retrieves results via RPC requests to the server.
 */
public class RpcDataSource implements DataSource {
    private String dataMethodName, countMethodName;
    protected JSONObject filterParams;
    private JSONObject lastRequestParams;
    protected Integer numResults = null;
    
    public RpcDataSource(String dataMethodName, String countMethodName) {
        this.dataMethodName = dataMethodName;
        this.countMethodName = countMethodName;
    }
    
    /**
     * Process the JSON result returned by the server into an array of result 
     * objects.  This default implementation assumes the result itself is an array.
     * Subclasses may override this to construct an array from the JSON result.
     */
    protected JSONArray handleJsonResult(JSONValue result) {
        return result.isArray();
    }
    
    public void updateData(JSONObject params, final DataCallback callback) {
        filterParams = params;
        JsonRpcProxy.getProxy().rpcCall(countMethodName, params, 
                                        new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                int count = (int) result.isNumber().doubleValue();
                numResults = Integer.valueOf(count);
                callback.onGotData(count);
            }

            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                callback.onError(errorObject);
            }
        });
    }
    
    public void getPage(Integer start, Integer maxCount, SortSpec[] sortOn, 
                        final DataCallback callback) {
        JSONObject params;
        if (filterParams == null)
            params = new JSONObject();
        else
            params = Utils.copyJSONObject(filterParams);
        if (start != null)
            params.put("query_start", new JSONNumber(start.intValue()));
        if (maxCount != null)
            params.put("query_limit", new JSONNumber(maxCount.intValue()));
        if (sortOn != null) {
            JSONArray sortList = new JSONArray();
            for (SortSpec sortSpec : sortOn) {
                sortList.set(sortList.size(), new JSONString(sortSpec.toString()));
            }
            params.put("sort_by", sortList);
        }
        
        lastRequestParams = params;
        JsonRpcProxy.getProxy().rpcCall(dataMethodName, params, 
                                        new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                JSONArray resultData = handleJsonResult(result);
                callback.handlePage(resultData);
            }

            @Override
            public void onError(JSONObject errorObject) {
                super.onError(errorObject);
                callback.onError(errorObject);
            }
        });
    }

    public int getNumResults() {
        assert numResults != null;
        return numResults.intValue();
    }

    public String getDataMethodName() {
        return dataMethodName;
    }

    public JSONObject getLastRequestParams() {
        return Utils.copyJSONObject(lastRequestParams);
    }
}
