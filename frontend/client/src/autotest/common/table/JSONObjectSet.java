package autotest.common.table;

import com.google.gwt.json.client.JSONObject;

import java.util.AbstractSet;
import java.util.Collection;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

/**
 * Set that hashes JSONObjects by their ID, so that identical objects get
 * matched together.
 */
public class JSONObjectSet<T extends JSONObject> extends AbstractSet<T> {
    protected Map<String, T> backingMap = new HashMap<String, T>();

    public JSONObjectSet() {
        super();
    }

    public JSONObjectSet(Collection<T> items) {
        super();
        addAll(items);
    }

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
