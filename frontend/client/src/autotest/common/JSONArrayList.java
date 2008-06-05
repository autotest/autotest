package autotest.common;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONValue;

import java.util.AbstractList;

/**
 * Wraps a JSONArray in a handy-dandy java.util.List interface.
 */
public class JSONArrayList extends AbstractList<JSONValue> {
    protected JSONArray backingArray;
    
    public JSONArrayList(JSONArray array) {
        backingArray = array;
    }
    
    public void add(int index, JSONValue object) {
        backingArray.set(index, object);
    }

    public JSONValue get(int index) {
        return backingArray.get(index);
    }

    // JSONArrays don't directly support this
    public JSONValue remove(int arg0) {
        throw new UnsupportedOperationException();
    }

    public int size() {
        return backingArray.size();
    }
}
