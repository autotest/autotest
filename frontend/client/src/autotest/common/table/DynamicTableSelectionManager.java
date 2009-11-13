package autotest.common.table;

import autotest.common.JSONArrayList;
import autotest.common.table.DataSource.DefaultDataCallback;
import autotest.common.table.DataSource.Query;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;

import java.util.List;
import java.util.Set;

public class DynamicTableSelectionManager extends SelectionManager {
    /**
     * see deselectFiltered()
     */
    private final DefaultDataCallback deselectFilteredCallback = new DefaultDataCallback() {
        @Override
        public void onQueryReady(Query query) {
            query.getPage(null, null, null, this);
        }

        @Override
        public void handlePage(List<JSONObject> data) {
            // use set intersection to get objects from the selected object set, rather than using
            // the objects returned by the server.  we have to do this because ArrayDataSource uses
            // object identity and not value equality of JSONObjects.
            Set<JSONObject> filteredRows = new JSONObjectSet<JSONObject>(data);
            Set<JSONObject> rowsToRemove = new JSONObjectSet<JSONObject>(getSelectedObjects());
            rowsToRemove.retainAll(filteredRows);
            deselectObjects(rowsToRemove);
        }
    };

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
        attachedDynamicTable.getCurrentQuery().getPage(null, null, null, new DefaultDataCallback() {
            @Override
            public void handlePage(List<JSONObject> data) {
                selectObjects(data);
            }
        });
    }

    @Override
    public void onSelectNone() {
        deselectFiltered();
    }

    /**
     * Only deselect items included in the current filters.
     */
    private void deselectFiltered() {
        if (!attachedDynamicTable.isAnyUserFilterActive()) {
            deselectAll();
            return;
        }
        
        JSONObject params = attachedDynamicTable.getCurrentQuery().getParams();
        params.put("id__in", selectedIdList());
        attachedDynamicTable.getDataSource().query(params, deselectFilteredCallback);
    }

    private JSONArray selectedIdList() {
        JSONArrayList<JSONNumber> idList = new JSONArrayList<JSONNumber>();
        for (JSONObject object : getSelectedObjects()) {
            JSONNumber id = object.get("id").isNumber();
            assert id != null;
            idList.add(id);
        }
        return idList.getBackingArray();
    }
}
