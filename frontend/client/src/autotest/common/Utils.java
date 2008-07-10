package autotest.common;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

public class Utils {
    private static final String[][] escapeMappings = {
        {"&", "&amp;"},
        {">", "&gt;"},
        {"<", "&lt;"},
        {"\"", "&quot;"},
        {"'", "&apos;"},
    };

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
    
    public static String escape(String text) {
        for (String[] mapping : escapeMappings) {
            text = text.replaceAll(mapping[0], mapping[1]);
        }
        return text;
    }
    
    public static String unescape(String text) {
        // must iterate in reverse order
        for (int i = escapeMappings.length - 1; i >= 0; i--) {
            text = text.replaceAll(escapeMappings[i][1], escapeMappings[i][0]);
        }
        return text;
    }
    
    public static <T> List<T> wrapObjectWithList(T object) {
        List<T> list = new ArrayList<T>();
        list.add(object);
        return list;
    }
    
    public static String joinStrings(String joiner, List<String> strings) {
        if (strings.size() == 0) {
            return "";
        }
        
        StringBuilder result = new StringBuilder(strings.get(0));
        for (int i = 1; i < strings.size(); i++) {
            result.append(joiner);
            result.append(strings.get(i));
        }
        return result.toString();
    }

}
