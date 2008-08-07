package autotest.tko;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;

import autotest.common.JSONArrayList;
import autotest.common.table.RpcDataSource;

class TestViewDataSource extends RpcDataSource {
    public TestViewDataSource() {
        super("get_test_views", "get_num_test_views");
    }

    /**
     * Add 'id' field, needed by SelectionManager.
     */
    @Override
    protected JSONArray handleJsonResult(JSONValue result) {
        JSONArray objects = super.handleJsonResult(result);
        for (JSONObject object : new JSONArrayList<JSONObject>(objects)) {
            object.put("id", object.get("test_idx"));
        }
        return objects;
    }
}
