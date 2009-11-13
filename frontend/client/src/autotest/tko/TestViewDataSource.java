package autotest.tko;

import autotest.common.table.RpcDataSource;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONValue;

import java.util.List;

class TestViewDataSource extends RpcDataSource {
    public TestViewDataSource() {
        super("get_test_views", "get_num_test_views");
    }

    /**
     * Add 'id' field, needed by SelectionManager.
     */
    @Override
    protected List<JSONObject> handleJsonResult(JSONValue result) {
        List<JSONObject> objects = super.handleJsonResult(result);
        for (JSONObject object : objects) {
            object.put("id", object.get("test_idx"));
        }
        return objects;
    }
}
