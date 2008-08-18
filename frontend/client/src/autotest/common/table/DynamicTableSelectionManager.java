package autotest.common.table;

import autotest.common.JSONArrayList;
import autotest.common.table.DataSource.DataCallback;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;

public class DynamicTableSelectionManager extends SelectionManager {
    private DynamicTable attachedDynamicTable;

    public DynamicTableSelectionManager(DynamicTable table, boolean selectOnlyOne) {
        super(table, selectOnlyOne);
        attachedDynamicTable = table;
    }


    @Override
    /**
     * Select all objects covering all pages, not just the currently displayed page in the table.
     */
    public void selectAll() {
        DataSource dataSource = attachedDynamicTable.getDataSource();
        dataSource.getPage(null, null, null, new DataCallback() {
            public void handlePage(JSONArray data) {
                selectObjects(new JSONArrayList<JSONObject>(data));
            }

            public void onGotData(int totalCount) {}
            public void onError(JSONObject errorObject) {}
        });
    }
}
