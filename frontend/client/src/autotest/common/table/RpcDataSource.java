package autotest.common.table;

import autotest.common.JSONArrayList;
import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.Utils;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.List;

/**
 * Data source that retrieves results via RPC requests to the server.
 */
public class RpcDataSource implements DataSource {
    private class RpcQuery extends DefaultQuery {
        public RpcQuery(JSONObject params) {
            super(params);
        }

        @Override
        public void getPage(Integer start, Integer maxCount, SortSpec[] sortOn,
                            final DataCallback callback) {
            JSONObject pageParams = Utils.copyJSONObject(params);
            if (start != null) {
                pageParams.put("query_start", new JSONNumber(start.intValue()));
            }
            if (maxCount != null) {
                pageParams.put("query_limit", new JSONNumber(maxCount.intValue()));
            }
            if (sortOn != null) {
                JSONArray sortList = new JSONArray();
                for (SortSpec sortSpec : sortOn) {
                    sortList.set(sortList.size(), new JSONString(sortSpec.toString()));
                }
                pageParams.put("sort_by", sortList);
            }

            JsonRpcProxy.getProxy().rpcCall(dataMethodName, pageParams, 
                                            new JsonRpcCallback() {
                @Override
                public void onSuccess(JSONValue result) {
                    List<JSONObject> resultData = handleJsonResult(result);
                    callback.handlePage(resultData);
                }

                @Override
                public void onError(JSONObject errorObject) {
                    super.onError(errorObject);
                    callback.onError(errorObject);
                }
            });
        }

        @Override
        public void getTotalResultCount(final DataCallback callback) {
            JsonRpcProxy.getProxy().rpcCall(countMethodName, params, 
                                            new JsonRpcCallback() {
                @Override
                public void onSuccess(JSONValue result) {
                    int count = (int) result.isNumber().doubleValue();
                    callback.handleTotalResultCount(count);
                }

                @Override
                public void onError(JSONObject errorObject) {
                    super.onError(errorObject);
                    callback.onError(errorObject);
                }
            });
        }
    }

    private String dataMethodName, countMethodName;
    
    public RpcDataSource(String dataMethodName, String countMethodName) {
        this.dataMethodName = dataMethodName;
        this.countMethodName = countMethodName;
    }
    
    /**
     * Process the JSON result returned by the server into an list of result 
     * objects.  This default implementation assumes the result itself is an array.
     * Subclasses may override this to construct a list from the JSON result in a customized way.
     */
    protected List<JSONObject> handleJsonResult(JSONValue result) {
        return new JSONArrayList<JSONObject>(result.isArray());
    }

    @Override
    public void query(JSONObject params, DataCallback callback) {
        callback.onQueryReady(new RpcQuery(params));
    }

    public String getDataMethodName() {
        return dataMethodName;
    }
}
