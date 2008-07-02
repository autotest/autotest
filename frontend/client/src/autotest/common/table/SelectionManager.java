package autotest.common.table;

import autotest.common.table.DynamicTable.DynamicTableListener;

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
    protected Set<JSONObject> selectedObjects = new JSONValueSet<JSONObject>();
    protected boolean selectOnlyOne = false;
    protected DynamicTable attachedTable;
    protected List<SelectionListener> listeners =
        new ArrayList<SelectionListener>();
    
    public interface SelectionListener {
        public void onAdd(Collection<JSONObject> objects);
        public void onRemove(Collection<JSONObject> objects);
    }
    
    
    /**
     * Set that hashes JSONObjects by their ID, so that identical objects get 
     * matched together.
     */
    static class JSONValueSet<T extends JSONObject> extends AbstractSet<T> {
        protected Map<String, T> backingMap = new HashMap<String, T>();
        
        protected String getKey(Object obj) {
            return ((JSONObject) obj).get("id").toString();
        }

        @Override
        public boolean add(T arg0) {
            return backingMap.put(getKey(arg0), arg0) == null;
        }

        @Override
        public Iterator<T> iterator() {
            return backingMap.values().iterator();
        }

        @Override
        public boolean remove(Object arg0) {
            return backingMap.remove(getKey(arg0)) != null;
        }

        @Override
        public boolean contains(Object o) {
            return backingMap.containsKey(getKey(o));
        }

        @Override
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
    
    protected Collection<JSONObject> wrapObject(JSONObject object) {
        List<JSONObject> list = new ArrayList<JSONObject>();
        list.add(object);
        return list;
    }
    
    public void selectObject(JSONObject object) {
        selectObjects(wrapObject(object));
    }
    
    public void selectObjects(Collection<? extends JSONObject> objects) {
        if (selectOnlyOne) {
            assert objects.size() == 1;
            deselectAll();
        }
        addOrRemoveObjects(objects, true);
    }
    
    public void deselectObject(JSONObject object) {
        deselectObjects(wrapObject(object));
    }
    
    public void deselectObjects(Collection<JSONObject> objects) {
        addOrRemoveObjects(objects, false);
    }
    
    protected void addOrRemoveObjects(Collection<? extends JSONObject> objects,
                                      boolean add) {
        List<JSONObject> actuallyUsed = new ArrayList<JSONObject>();
        for (JSONObject object : objects) {
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
        List<JSONObject> removed = new ArrayList<JSONObject>(selectedObjects);
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
        return selectedObjects.iterator().next();
    }
    
    public Set<JSONObject> getSelectedObjects() {
        return selectedObjects;
    }
    
    public void addListener(SelectionListener listener) {
        listeners.add(listener);
    }
    
    public void removeListener(SelectionListener listener) {
        listeners.remove(listener);
    }
    
    protected void notifyListeners(JSONObject object, boolean add) {
        List<JSONObject> objectList = new ArrayList<JSONObject>();
        objectList.add(object);
        notifyListeners(objectList, add);
    }
    
    protected void notifyListeners(Collection<JSONObject> objects,
                                   boolean add) {
        for (SelectionListener listener : listeners) {
            if (add)
                listener.onAdd(objects);
            else
                listener.onRemove(objects);
        }
    }
}
