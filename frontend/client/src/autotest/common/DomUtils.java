package autotest.common;

import com.google.gwt.dom.client.Element;

public class DomUtils {
    public static void clearDomChildren(Element elem) {
        Element child = elem.getFirstChildElement();
        while (child != null) {
            Element nextChild = child.getNextSiblingElement();
            elem.removeChild(child);
            child = nextChild;
        }
    }
}
