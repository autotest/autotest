package autotest.tko;

import autotest.common.JSONArrayList;
import autotest.common.JsonRpcCallback;
import autotest.common.JsonRpcProxy;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;

import com.google.gwt.dom.client.Element;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.DOM;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class TkoUtils {
    private static StaticDataRepository staticData = StaticDataRepository.getRepository();
    private static JsonRpcProxy rpcProxy = JsonRpcProxy.getProxy();
    public static final ClassFactory factory = new SiteClassFactory();
    
    public static class FieldInfo {
        public String field;
        public String name;
        
        public FieldInfo(String field, String name) {
            this.field = field;
            this.name = name;
        }
    }
    
    public static List<FieldInfo> getFieldList(String listName) {
        JSONArray fieldArray = staticData.getData(listName).isArray();
        List<FieldInfo> fields = new ArrayList<FieldInfo>();
        for (JSONArray fieldTuple : new JSONArrayList<JSONArray>(fieldArray)) {
            String fieldName = fieldTuple.get(0).isString().stringValue();
            String field = fieldTuple.get(1).isString().stringValue();
            fields.add(new FieldInfo(field, fieldName));
        }
        return fields;
    }

    protected static JSONObject getConditionParams(String condition) {
        JSONObject params = new JSONObject();
        params.put("extra_where", new JSONString(condition));
        return params;
    }

    protected static void getTestId(TestSet test, final TestSelectionListener listener) {
        rpcProxy.rpcCall("get_test_views", test.getCondition(), new JsonRpcCallback() {
            @Override
            public void onSuccess(JSONValue result) {
                // just take the first result (there could be more than one due to
                // a rare and harmless race condition)
                JSONObject testView = result.isArray().get(0).isObject();
                int testId = (int) testView.get("test_idx").isNumber().doubleValue();
                listener.onSelectTest(testId);
            }
        });
    }

    protected static void clearDomChildren(Element elem) {
        Element child = elem.getFirstChildElement();
        while (child != null) {
            Element nextChild = child.getNextSiblingElement();
            elem.removeChild(child);
            child = nextChild;
        }
    }

    static void setElementVisible(String elementId, boolean visible) {
        DOM.getElementById(elementId).getStyle().setProperty("display", visible ? "" : "none");
    }

    static String getSqlCondition(JSONObject args) {
        final JSONValue condition = args.get("extra_where");
        if (condition == null) {
            return "";
        }
        return condition.isString().stringValue();
    }
    
    static String wrapWithParens(String string) {
        if (string.equals("")) {
            return string;
        }
        return "(" + string + ")";
    }
    
    static String joinWithParens(String joiner, String first, String second) {
        first = wrapWithParens(first);
        second = wrapWithParens(second);
        return Utils.joinStrings(" AND ", Arrays.asList(new String[] {first, second}));
    }
}
