package autotest.common;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONValue;

import java.util.AbstractList;

/**
 * Wraps a JSONArray in a handy-dandy java.util.List interface.
 */
public class JSONArrayList<T extends JSONValue> extends AbstractList<T> {
    private JSONArray backingArray;
    
    public JSONArrayList() {
        backingArray = new JSONArray();
    }
    
    public JSONArrayList(JSONArray array) {
        backingArray = array;
    }
    
    @Override
    public void add(int index, T object) {
        backingArray.set(index, object);
    }

    @SuppressWarnings("unchecked")
    @Override
    public T get(int index) {
        return (T) backingArray.get(index);
    }

    // JSONArrays don't directly support this
    @Override
    public T remove(int arg0) {
        throw new UnsupportedOperationException();
    }

    @Override
    public int size() {
        return backingArray.size();
    }
    
    public JSONArray getBackingArray() {
        return backingArray;
    }
}
