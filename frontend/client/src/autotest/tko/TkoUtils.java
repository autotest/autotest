package autotest.tko;

import autotest.common.JSONArrayList;
import autotest.common.JsonRpcProxy;
import autotest.common.StaticDataRepository;
import autotest.common.Utils;
import autotest.common.table.RpcDataSource;

import com.google.gwt.dom.client.Element;
import com.google.gwt.http.client.URL;
import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;
import com.google.gwt.user.client.DOM;
import com.google.gwt.user.client.ui.FlexTable;
import com.google.gwt.user.client.ui.Widget;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class TkoUtils {
    private static StaticDataRepository staticData = StaticDataRepository.getRepository();
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
        return Utils.joinStrings(joiner, Arrays.asList(new String[] {first, second}));
    }

    static String escapeSqlValue(String value) {
        return value.replace("\\", "\\\\").replace("'", "\\'");
    }
    
    static int addControlRow(FlexTable table, String text, Widget control) {
        int row = table.getRowCount();
        table.setText(row, 0, text);
        table.getFlexCellFormatter().setStylePrimaryName(row, 0, "field-name");
        table.setWidget(row, 1, control);
        return row;
    }
    
    static void doCsvRequest(RpcDataSource dataSource, JSONObject extraParams) {
        String rpcMethodName = dataSource.getDataMethodName();
        JSONObject arguments = dataSource.getLastRequestParams();
        // remove pagination arguments, since the user will want to export all results
        arguments.put("query_start", null);
        arguments.put("query_limit", null);

        JSONObject request = JsonRpcProxy.buildRequestObject(rpcMethodName, arguments);
        if (extraParams != null) {
            Utils.updateObject(request, extraParams);
        }
        
        String url = JsonRpcProxy.TKO_BASE_URL + "csv/?" + URL.encode(request.toString());
        Utils.openUrlInNewWindow(url);
    }
    
    static void doCsvRequest(RpcDataSource dataSource) {
        doCsvRequest(dataSource, null);
    }
}
