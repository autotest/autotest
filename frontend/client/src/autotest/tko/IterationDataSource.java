package autotest.tko;

import autotest.common.Utils;
import autotest.common.table.RpcDataSource;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.List;

public class IterationDataSource extends RpcDataSource {
    public IterationDataSource() {
        super("get_iteration_views", "get_num_iteration_views");
    }

    /**
     * Add 'id' field, needed by SelectionManager.
     */
    @Override
    protected List<JSONObject> handleJsonResult(JSONValue result) {
        List<JSONObject> objects = super.handleJsonResult(result);
        for (JSONObject object : objects) {
            String iterationId = Utils.jsonToString(object.get("test_idx")) + "-"
                    + Utils.jsonToString(object.get("iteration_index"));
            object.put("id", new JSONString(iterationId));
        }
        return objects;
    }
}
