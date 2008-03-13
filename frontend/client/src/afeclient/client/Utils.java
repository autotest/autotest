package afeclient.client;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;

import java.util.Collection;
import java.util.Iterator;
import java.util.Set;

/**
 * Utility methods.
 */
public class Utils {
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
        for (int i = 0; i < strings.size(); i++)
            result[i] = strings.get(i).isString().stringValue();
        return result;
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
}
