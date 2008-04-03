package afeclient.client.table;

import afeclient.client.table.DynamicTable.DynamicTableListener;

import com.google.gwt.json.client.JSONObject;

import java.util.AbstractSet;
import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;

public class SelectionManager {
    protected Set selectedObjects = new JSONValueSet();
    protected boolean selectOnlyOne = false;
    protected DynamicTable attachedTable;
    protected List listeners = new ArrayList();
    
    public interface SelectionListener {
        public void onAdd(Collection objects);
        public void onRemove(Collection objects);
    }
    
    
    /**
     * Set that hashes JSONObjects by their ID, so that identical objects get 
     * matched together.
     */
    class JSONValueSet extends AbstractSet {
        protected Map backingMap = new HashMap();
        
        protected String getKey(Object obj) {
            return ((JSONObject) obj).get("id").toString();
        }

        public boolean add(Object arg0) {
            return backingMap.put(getKey(arg0), arg0) == null;
        }

        public Iterator iterator() {
            return backingMap.values().iterator();
        }

        public boolean remove(Object arg0) {
            return backingMap.remove(getKey(arg0)) != null;
        }

        public boolean contains(Object o) {
            return backingMap.containsKey(getKey(o));
        }

        public int size() {
            return backingMap.size();
        }
    }
    
    public SelectionManager(DynamicTable table, boolean selectOnlyOne) {
        attachedTable = table;
        this.selectOnlyOne = selectOnlyOne;
        
        table.addListener(new DynamicTableListener() {
            public void onRowClicked(int rowIndex, JSONObject row) {
                toggleSelected(row);
                refreshSelection();
            } 
            
            public void onTableRefreshed() {
                refreshSelection();
            }
        });
    }
    
    public void refreshSelection() {
        for (int i = 0; i < attachedTable.getRowCount(); i++) {
            if (selectedObjects.contains(attachedTable.getRow(i)))
                attachedTable.highlightRow(i);
            else
                attachedTable.unhighlightRow(i);
        }
    }
    
    protected Collection wrapObject(Object object) {
        List list = new ArrayList();
        list.add(object);
        return list;
    }
    
    public void selectObject(JSONObject object) {
        selectObjects(wrapObject(object));
    }
    
    public void selectObjects(Collection objects) {
        if (selectOnlyOne) {
            assert objects.size() == 1;
            deselectAll();
        }
        addOrRemoveObjects(objects, true);
    }
    
    public void deselectObject(JSONObject object) {
        deselectObjects(wrapObject(object));
    }
    
    public void deselectObjects(Collection objects) {
        addOrRemoveObjects(objects, false);
    }
    
    protected void addOrRemoveObjects(Collection objects, boolean add) {
        List actuallyUsed = new ArrayList();
        for (Iterator i = objects.iterator(); i.hasNext(); ) {
            Object object = i.next();
            boolean used = false;
            if (add)
                used = selectedObjects.add(object);
            else
                used = selectedObjects.remove(object);
            if (used)
                actuallyUsed.add(object);
        }
        notifyListeners(actuallyUsed, add);
    }
    
    public void deselectAll() {
        List removed = new ArrayList(selectedObjects);
        selectedObjects.clear();
        notifyListeners(removed, false);
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
        return (JSONObject) selectedObjects.iterator().next();
    }
    
    public Set getSelectedObjects() {
        return selectedObjects;
    }
    
    public void addListener(SelectionListener listener) {
        listeners.add(listener);
    }
    
    public void removeListener(SelectionListener listener) {
        listeners.remove(listener);
    }
    
    protected void notifyListeners(JSONObject object, boolean add) {
        List objectList = new ArrayList();
        objectList.add(object);
        notifyListeners(objectList, add);
    }
    
    protected void notifyListeners(Collection objects, boolean add) {
        for (Iterator i = listeners.iterator(); i.hasNext(); ) {
            SelectionListener listener = (SelectionListener) i.next();
            if (add)
                listener.onAdd(objects);
            else
                listener.onRemove(objects);
        }
    }
}
