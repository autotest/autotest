package autotest.common;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.Collection;

public class Utils {

    /**
     * Converts a collection of Java <code>String</code>s into a <code>JSONArray
     * </code> of <code>JSONString</code>s.
     */
    public static JSONArray stringsToJSON(Collection<String> strings) {
        JSONArray result = new JSONArray();
        for(String s : strings) {
            result.set(result.size(), new JSONString(s));
        }
        return result;
    }

    /**
     * Converts a <code>JSONArray</code> of <code>JSONStrings</code> to an 
     * array of Java <code>Strings</code>.
     */
    public static String[] JSONtoStrings(JSONArray strings) {
        String[] result = new String[strings.size()];
        for (int i = 0; i < strings.size(); i++) {
            result[i] = strings.get(i).isString().stringValue();
        }
        return result;
    }

    /**
     * Converts a <code>JSONArray</code> of <code>JSONObjects</code> to an 
     * array of Java <code>Strings</code> by grabbing the specified field from
     * each object.
     */
    public static String[] JSONObjectsToStrings(JSONArray objects, String field) {
        String[] result = new String[objects.size()];
        for (int i = 0; i < objects.size(); i++) {
            JSONValue fieldValue = objects.get(i).isObject().get(field);
            result[i] = fieldValue.isString().stringValue();
        }
        return result;
    }

    /**
     * Get a value out of an array of size 1.
     * @return array[0]
     * @throws IllegalArgumentException if the array is not of size 1
     */
    public static JSONValue getSingleValueFromArray(JSONArray array) {
        if(array.size() != 1) {
            throw new IllegalArgumentException("Array is not of size 1");
        }
        return array.get(0);
    }

    public static JSONObject copyJSONObject(JSONObject source) {
        JSONObject dest = new JSONObject();
        for(String key : source.keySet()) {
            dest.put(key, source.get(key));
        }
        return dest;
    }

}
