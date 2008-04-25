package afeclient.client;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

import java.util.Collection;
import java.util.Iterator;
import java.util.Set;

/**
 * Utility methods.
 */
public class Utils {
    public static final String PLATFORM_SUFFIX = " (platform)";
    
    public static final ClassFactory factory = new SiteClassFactory();
    
    /**
     * Converts a collection of Java <code>String</code>s into a <code>JSONArray
     * </code> of <code>JSONString</code>s.
     */
    public static JSONArray stringsToJSON(Collection strings) {
        JSONArray result = new JSONArray();
        for(Iterator i = strings.iterator(); i.hasNext(); ) {
            String s = (String) i.next();
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
    
    public static String formatStatusCounts(JSONObject counts, String joinWith) {
        String result = "";
        Set statusSet = counts.keySet();
        for (Iterator i = statusSet.iterator(); i.hasNext();) {
            String status = (String) i.next();
            int count = (int) counts.get(status).isNumber().getValue();
            result += Integer.toString(count) + " " + status;
            if (i.hasNext())
                result += joinWith;
        }
        return result;
    }
    
    public static JSONObject copyJSONObject(JSONObject source) {
        JSONObject dest = new JSONObject();
        for(Iterator i = source.keySet().iterator(); i.hasNext(); ) {
            String key = (String) i.next();
            dest.put(key, source.get(key));
        }
        return dest;
    }
    
    public static String[] getLabelStrings() {
        StaticDataRepository staticData = StaticDataRepository.getRepository();
        JSONArray labels = staticData.getData("labels").isArray();
        String[] result = new String[labels.size()];
        for (int i = 0; i < labels.size(); i++) {
            JSONObject label = labels.get(i).isObject();
            String name = label.get("name").isString().stringValue();
            boolean platform = label.get("platform").isNumber().getValue() != 0;
            if (platform) {
                name += PLATFORM_SUFFIX;
            }
            result[i] = name;
        }
        return result;
    }
    
    public static String decodeLabelName(String labelName) {
        if (labelName.endsWith(PLATFORM_SUFFIX)) {
            int nameLength = labelName.length() - PLATFORM_SUFFIX.length();
            return labelName.substring(0, nameLength);
        }
        return labelName;
    }
}
