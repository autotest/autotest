package autotest.common.table;

import autotest.common.Utils;
import autotest.common.table.DataTable.TableWidgetFactory;
import autotest.common.table.TableClickWidget.TableWidgetClickListener;
import autotest.common.ui.TableSelectionPanel.SelectionPanelListener;

import com.google.gwt.json.client.JSONObject;
import com.google.gwt.user.client.ui.CheckBox;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Collection;
import java.util.Collections;
import java.util.List;
import java.util.Set;

/**
 * This class manages a selection of rows on a DataTable.  It keeps track of selected objects and
 * takes care of highlighting rows.  It can also be used for a DynamicTable, with support for paging
 * etc., if you use DynamicTableSelectionManager.
 * 
 * For convenience, it can also act as a TableWidgetFactory to supply checkboxes for selecting rows 
 * in a table, and as a SelectionPanelListener.
 *
 */
public class SelectionManager implements TableWidgetFactory, TableWidgetClickListener,
                                         SelectionPanelListener {
    private Set<JSONObject> selectedObjects = new JSONObjectSet<JSONObject>();
    private boolean selectOnlyOne = false;
    private DataTable attachedTable;
    private List<SelectionListener> listeners = new ArrayList<SelectionListener>();
    private SelectableRowFilter selectableRowFilter;
    
    public interface SelectionListener {
        public void onAdd(Collection<JSONObject> objects);
        public void onRemove(Collection<JSONObject> objects);
    }
    
    public interface SelectableRowFilter {
        public boolean isRowSelectable(JSONObject row);
    }
    
    public SelectionManager(DataTable table, boolean selectOnlyOne) {
        attachedTable = table;
        this.selectOnlyOne = selectOnlyOne;
    }
    
    public void setSelectableRowFilter(SelectableRowFilter filter) {
        selectableRowFilter = filter;
    }
    
    public void refreshSelection() {
        for (int i = 0; i < attachedTable.getRowCount(); i++) {
            JSONObject row = attachedTable.getRow(i);
            if (!isSelectable(row)) {
                continue;
            }
            if (selectedObjects.contains(row)) { 
                attachedTable.highlightRow(i);
            } else {
                attachedTable.unhighlightRow(i);
            }
        }
        attachedTable.refreshWidgets();
    }
    
    private boolean isSelectable(JSONObject row) {
        if (selectableRowFilter != null) {
            return selectableRowFilter.isRowSelectable(row);
        }
        return true;
    }

    public void selectObject(JSONObject object) {
        selectObjects(Utils.wrapObjectWithList(object));
    }
    
    public void selectObjects(Collection<? extends JSONObject> objects) {
        if (selectOnlyOne) {
            assert objects.size() == 1;
            deselectAll();
        }
        addOrRemoveObjects(objects, true);
    }
    
    public void deselectObject(JSONObject object) {
        deselectObjects(Utils.wrapObjectWithList(object));
    }
    
    public void deselectObjects(Collection<JSONObject> objects) {
        addOrRemoveObjects(objects, false);
    }
    
    protected void addOrRemoveObjects(Collection<? extends JSONObject> objects,
                                      boolean add) {
        List<JSONObject> actuallyUsed = new ArrayList<JSONObject>();
        for (JSONObject object : objects) {
            if (!isSelectable(object)) {
                continue;
            }
            boolean used = false;
            if (add) {
                used = selectedObjects.add(object);
            } else {
                used = selectedObjects.remove(object);
            }
            if (used) {
                actuallyUsed.add(object);
            }
        }
        notifyListeners(actuallyUsed, add);
    }
    
    /*
     * Select all objects in the table.
     */
    public void selectAll() {
        selectVisible();
    }
    
    public void deselectAll() {
        List<JSONObject> removed = new ArrayList<JSONObject>(selectedObjects);
        selectedObjects.clear();
        notifyListeners(removed, false);
    }
    
    public void selectVisible() {
        selectObjects(attachedTable.getAllRows());
    }
    
    public void toggleSelected(JSONObject object) {
        if (selectedObjects.contains(object))
            deselectObject(object);
        else
            selectObject(object);
    }
    
    public JSONObject getSelectedOne() {
        assert selectOnlyOne;
        if (selectedObjects.isEmpty())
            return null;
        return selectedObjects.iterator().next();
    }
    
    public Set<JSONObject> getSelectedObjects() {
        return Collections.unmodifiableSet(selectedObjects);
    }
    
    public boolean isEmpty() {
        return selectedObjects.isEmpty();
    }
    
    public void addListener(SelectionListener listener) {
        listeners.add(listener);
    }
    
    public void removeListener(SelectionListener listener) {
        listeners.remove(listener);
    }
    
    protected void notifyListeners(Collection<JSONObject> objects,
                                   boolean add) {
        refreshSelection();
        for (SelectionListener listener : listeners) {
            if (add)
                listener.onAdd(objects);
            else
                listener.onRemove(objects);
        }
    }

    // code for acting as a TableWidgetFactory/TableWidgetClickListener
    
    public Widget createWidget(int row, int cell, JSONObject rowObject) {
        if (!isSelectable(rowObject)) {
            return null;
        }

        CheckBox checkBox = new CheckBox();
        if(selectedObjects.contains(rowObject)) {
            checkBox.setValue(true);
        }
        return new TableClickWidget(checkBox, this, row, cell);
    }

    public void onClick(TableClickWidget widget) {
        toggleSelected(attachedTable.getRow(widget.getRow()));
        refreshSelection();
    }
    
    // code for acting as a SelectionPanelListener

    public void onSelectAll(boolean visibleOnly) {
        if (visibleOnly) {
            selectVisible();
        } else {
            selectAll();
        }
    }

    public void onSelectNone() {
        deselectAll();
    }
}
